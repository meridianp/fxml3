# Data Leakage Prevention Guide

## Overview

This document provides comprehensive guidance on preventing data leakage in the FXML4 ML feature engineering pipeline. Data leakage occurs when information from the future is inadvertently used to make predictions about the past, leading to unrealistically optimistic model performance that doesn't generalize to real trading.

## What is Data Leakage?

Data leakage in financial ML occurs when:
1. **Look-ahead bias**: Using future information to predict past events
2. **Information leakage**: Including features that wouldn't be available at prediction time
3. **Target leakage**: Using information derived from the target variable
4. **Temporal leakage**: Incorrect temporal alignment of features and targets

## Critical Fixes Implemented

### 1. Elliott Wave Features (FIXED)

**Problem**: The original Elliott Wave feature calculation used future data within window calculations.

**Location**: `/home/cnross/code/fxml4/fxml4/features/feature_engineering.py` - `_add_elliott_wave_features()`

**Fix Applied**:
```python
# BEFORE (Problematic):
window_data = df.iloc[max(0, i-window_size):i]  # Included current point

# AFTER (Fixed):
window_data = df.iloc[max(0, i-window_size):i]  # Excludes current point
```

**Explanation**: Now uses only historical data (from `i-window_size` to `i-1`) to calculate Elliott Wave features for time point `i`.

### 2. Target Label Creation (FIXED)

**Problem**: Target creation needed proper temporal validation warnings.

**Location**: `/home/cnross/code/fxml4/fxml4/ml/features.py` - `create_target_labels()`

**Fix Applied**:
- Added explicit warnings about temporal alignment
- Added validation that last `horizon` rows have NaN targets
- Documented that `shift(-horizon)` is intentional for training data

### 3. Temporal Integrity Validation (NEW)

**Location**: `/home/cnross/code/fxml4/fxml4/ml/features.py` - `validate_temporal_integrity()`

**Purpose**: Automatically detect potential data leakage through:
- Target alignment validation
- Feature calculation window validation
- Correlation analysis with future data
- NaN pattern validation

## Data Leakage Prevention Rules

### Rule 1: Window-Based Calculations

✅ **CORRECT**: Use only historical data
```python
# For calculating feature at time t, use data from [t-window, t-1]
window_data = df.iloc[max(0, i-window_size):i]  # Excludes current point
```

❌ **INCORRECT**: Including current or future data
```python
# Don't include current point in calculation
window_data = df.iloc[max(0, i-window_size):i+1]  # Includes current point
# Don't use future data
window_data = df.iloc[i:i+window_size]  # Uses future data
```

### Rule 2: Rolling Statistics

✅ **CORRECT**: Pandas rolling with proper alignment
```python
# Moving average at time t uses [t-n+1, t]
df['sma_20'] = df['close'].rolling(window=20).mean()
```

❌ **INCORRECT**: Manual calculations that might shift alignment
```python
# Avoid manual calculations that might misalign
for i in range(len(df)):
    df.loc[i, 'sma_20'] = df['close'].iloc[i-19:i+1].mean()  # Could shift alignment
```

### Rule 3: Target Variable Creation

✅ **CORRECT**: Explicit future data usage for training
```python
# For training data, this is correct - uses future data intentionally
future_return = df["close"].shift(-horizon) / df["close"] - 1
# Last 'horizon' rows will have NaN targets (correct)
```

❌ **INCORRECT**: Using targets for feature creation
```python
# Don't use future targets to create features
df['target_derived_feature'] = df['target'].rolling(10).mean()  # Uses future info
```

### Rule 4: Feature Engineering Pipeline

✅ **CORRECT**: Temporal ordering
```python
# 1. Calculate features using only historical data
features = calculate_features(data)
# 2. Create targets using appropriate horizon
targets = create_targets(data, horizon=10)
# 3. Align features and targets temporally
final_data = align_features_targets(features, targets)
```

## Testing for Data Leakage

### 1. Automated Testing

Run the comprehensive test suite:
```bash
pytest tests/unit/test_data_leakage_prevention.py -v
```

### 2. Manual Validation

Use the validation function:
```python
from fxml4.ml.features import validate_temporal_integrity

validation_results = validate_temporal_integrity(
    data=your_dataset,
    feature_cols=feature_columns,
    target_col='target_10',
    horizon=10
)

if not validation_results['temporal_integrity_passed']:
    print("Issues found:", validation_results['issues_found'])
    print("Warnings:", validation_results['warnings'])
```

### 3. Future Data Sensitivity Test

```python
def test_future_data_sensitivity(data, feature_func, test_idx=500):
    """Test if features at time t change when future data changes."""

    # Calculate features with original data
    original_features = feature_func(data)
    original_value = original_features.iloc[test_idx]

    # Modify future data dramatically
    modified_data = data.copy()
    modified_data.iloc[test_idx+1:] *= 2  # Large change

    # Recalculate features
    modified_features = feature_func(modified_data)
    modified_value = modified_features.iloc[test_idx]

    # Values should be identical (no look-ahead bias)
    assert abs(original_value - modified_value) < 1e-8
```

## Common Data Leakage Patterns to Avoid

### 1. Incorrect Shift Operations

❌ **AVOID**:
```python
# Using future data for current features
df['future_price'] = df['close'].shift(-1)  # Look-ahead bias
df['feature'] = df['close'] / df['future_price']  # Uses future data
```

### 2. Incorrect Window Alignment

❌ **AVOID**:
```python
# Including current point in rolling calculations inappropriately
df['forward_looking_ma'] = df['close'].rolling(window=20, center=True).mean()
```

### 3. Information from Target Variable

❌ **AVOID**:
```python
# Using target-derived information
df['target_ma'] = df['target'].rolling(10).mean()  # Target leakage
```

### 4. Incorrect Train/Test Splitting

❌ **AVOID**:
```python
# Random splitting of time series data
X_train, X_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

✅ **CORRECT**:
```python
# Temporal splitting preserves time order
split_idx = int(len(data) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
```

## Best Practices for Real-Time Deployment

### 1. Feature Calculation Order

Always calculate features in the same order as during training:
```python
def calculate_features_for_trading(current_data):
    """Calculate features for real-time trading."""
    # Use the same feature engineering pipeline as training
    feature_engineer = UnifiedFeatureEngineer(config)
    features = feature_engineer.generate_features(current_data)

    # Return only the most recent feature vector
    return features.iloc[-1]
```

### 2. Data Availability Simulation

Test your pipeline with limited data:
```python
def test_incremental_features(full_data, start_idx=100):
    """Test that features can be calculated incrementally."""
    for i in range(start_idx, len(full_data)):
        # Simulate real-time: only data up to time i is available
        available_data = full_data.iloc[:i+1]
        features = calculate_features(available_data)
        # Verify the feature calculation succeeds
        assert not features.iloc[-1].isna().all()
```

### 3. Latency Considerations

Ensure features can be calculated quickly:
```python
import time

def test_feature_calculation_speed(data):
    """Test that features can be calculated within acceptable time."""
    start_time = time.time()
    features = calculate_features(data)
    calculation_time = time.time() - start_time

    # Should calculate in under 1 second for real-time trading
    assert calculation_time < 1.0, f"Feature calculation too slow: {calculation_time}s"
```

## Validation Checklist

Before deploying any feature engineering changes:

- [ ] Run `pytest tests/unit/test_data_leakage_prevention.py`
- [ ] Use `validate_temporal_integrity()` function
- [ ] Verify last `horizon` rows have NaN targets
- [ ] Test future data sensitivity
- [ ] Check feature calculation speed
- [ ] Validate with walk-forward analysis
- [ ] Test incremental feature calculation
- [ ] Review for any `shift(-n)` operations in feature code
- [ ] Ensure proper temporal train/test splitting
- [ ] Document any intentional future data usage

## Emergency Data Leakage Detection

If you suspect data leakage in production:

1. **Immediate Check**:
   ```python
   # Check for suspiciously high correlations
   correlation = features.corrwith(future_returns)
   suspicious = correlation[correlation.abs() > 0.9]
   print("Suspicious correlations:", suspicious)
   ```

2. **Detailed Analysis**:
   ```python
   # Run full validation
   results = validate_temporal_integrity(data, feature_cols, target_col, horizon)
   if not results['temporal_integrity_passed']:
       print("CRITICAL: Data leakage detected!")
       print("Issues:", results['issues_found'])
   ```

3. **Rollback Procedure**:
   - Stop live trading immediately
   - Revert to previous feature engineering version
   - Investigate the specific feature causing leakage
   - Re-train models with corrected features
   - Test thoroughly before re-deployment

## Resources and References

- **Test File**: `tests/unit/test_data_leakage_prevention.py`
- **Validation Function**: `fxml4.ml.features.validate_temporal_integrity()`
- **Feature Engineering**: `fxml4.features.feature_engineering.UnifiedFeatureEngineer`
- **Main ML Features**: `fxml4.ml.features`

## Contact and Support

For questions about data leakage prevention:
1. Review this guide first
2. Run the automated tests
3. Use the validation functions
4. Check the test examples for proper usage patterns

Remember: **Prevention is better than detection**. Design your features with temporal integrity in mind from the start.
