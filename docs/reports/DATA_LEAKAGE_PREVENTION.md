# Data Leakage Prevention in FXML4

## Why Price Columns Are Excluded from Features

You're absolutely correct - preventing data leakage is CRITICAL for ML training. The current architecture is designed specifically to prevent this.

## Types of Data Leakage to Prevent

### 1. Direct Price Leakage
**Problem**: Using current bar's OHLC to predict current bar's return
```python
# WRONG - Severe leakage!
features = ['open', 'high', 'low', 'close']  # Current bar prices
target = (close - open) / open  # Current bar return

# The model would learn: if close > open, predict positive return
# This is useless for real trading!
```

### 2. Look-Ahead Bias
**Problem**: Using future information to make predictions
```python
# WRONG - Look-ahead bias!
df['sma_20'] = df['close'].rolling(20).mean()  # Uses future closes
df['target'] = df['close'].shift(-1)  # Next bar's close

# If SMA calculation includes future prices, it's cheating
```

### 3. Target Leakage
**Problem**: Features that encode information about the target
```python
# WRONG - Target leakage!
df['high_low_spread'] = df['high'] - df['low']  # Current bar
df['target'] = df['high_low_spread'].shift(-1)  # Next bar's volatility

# Current volatility often predicts next volatility
```

## Current Architecture (Correct Design)

### Feature Engineering Phase
```python
# 1. Calculate features using PAST data only
df['rsi_14'] = calculate_rsi(df['close'].shift(1), 14)  # Yesterday's RSI
df['sma_20'] = df['close'].shift(1).rolling(20).mean()  # Past 20 days
df['returns_1'] = df['close'].pct_change(1)  # Yesterday's return

# 2. Create target using FUTURE data
df['target'] = df['close'].pct_change(1).shift(-1)  # Tomorrow's return

# 3. Remove price columns to prevent accidental leakage
feature_cols = [col for col in df.columns if col not in ['open','high','low','close','volume']]
df_features = df[feature_cols]

# 4. Save features separately
df_features.to_parquet('EURUSD_h4_features.parquet')
```

### Why This Prevents Leakage

1. **No current bar prices in features** - Model can't cheat by looking at today's close
2. **All indicators use shifted data** - RSI, SMA etc. use yesterday's values
3. **Clear separation** - Features (past) vs Target (future)

## The Backtesting Challenge

During backtesting, we need both:
- **Features** (for prediction) - No price data
- **Prices** (for execution) - Current bar's OHLC

This is why we load both datasets:
```python
# Correct approach
features = load_features()  # Past data only
prices = load_prices()      # Current prices for execution

# Make prediction using features
signal = model.predict(features[timestamp])

# Execute using current price
execute_trade(prices[timestamp]['close'])
```

## Alternative: Single File with Careful Usage

We COULD keep everything in one file, but must be VERY careful:
```python
# Complete data file
df = pd.DataFrame({
    'open': ...,
    'high': ...,
    'low': ...,
    'close': ...,
    # ... features ...
    'target': ...
})

# During training - MUST exclude price columns
PRICE_COLS = ['open', 'high', 'low', 'close', 'volume']
feature_cols = [col for col in df.columns if col not in PRICE_COLS + ['target']]
X_train = df[feature_cols]  # No price leakage

# During backtesting - can use everything
current_price = df.loc[timestamp, 'close']
current_features = df.loc[timestamp, feature_cols]
```

## Common Leakage Mistakes in Forex ML

1. **Using current bar's high/low**
   ```python
   # WRONG
   df['high_low_ratio'] = df['high'] / df['low']  # Current bar

   # CORRECT
   df['high_low_ratio'] = df['high'].shift(1) / df['low'].shift(1)  # Previous bar
   ```

2. **Incomplete shifting**
   ```python
   # WRONG
   df['volatility'] = df['returns'].rolling(20).std()  # Includes current

   # CORRECT
   df['volatility'] = df['returns'].shift(1).rolling(20).std()  # Past only
   ```

3. **Using spread/slippage data**
   ```python
   # WRONG
   df['spread'] = df['ask'] - df['bid']  # Current spread

   # CORRECT
   df['spread_ma'] = df['spread'].shift(1).rolling(100).mean()  # Historical average
   ```

## Validation Techniques

### 1. Time-Based Split
```python
# NEVER use random train/test split for time series!
train = df[df.index < '2023-01-01']
test = df[df.index >= '2023-01-01']
```

### 2. Purged Cross-Validation
```python
# Add gap between train and test to prevent leakage
train_end = '2022-12-25'
test_start = '2023-01-01'  # 5-day gap
```

### 3. Feature Importance Check
```python
# If price columns show high importance, there's leakage!
if 'close' in top_features or 'high' in top_features:
    raise ValueError("Possible data leakage detected!")
```

## Conclusion

The current architecture (separate features and prices) is **correct** for preventing data leakage. While it adds complexity during backtesting, it ensures:

1. **No accidental price leakage** during training
2. **Clear separation** of past (features) and future (target)
3. **Reproducible results** in production

The inconvenience of loading two files is a small price to pay for ensuring our ML models are learning real patterns, not cheating with leaked data.

## Best Practices Summary

✅ **DO**: Keep features and prices separate during training
✅ **DO**: Shift all indicators to use only past data
✅ **DO**: Validate with proper time-based splits
✅ **DO**: Check feature importance for leakage

❌ **DON'T**: Include current bar OHLC in features
❌ **DON'T**: Use future data in any calculation
❌ **DON'T**: Random shuffle time series data
❌ **DON'T**: Trust results without leakage checks
