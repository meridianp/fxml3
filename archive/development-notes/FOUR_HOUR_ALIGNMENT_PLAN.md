# 4-Hour System Alignment Plan

## Critical Issue Identified
The system was designed for 4-hour bars but we've been training and backtesting with daily bars. This fundamental mismatch explains the poor performance.

## Impact of Daily vs 4-Hour Mismatch

### Feature Calculation Issues
- **Moving Averages**: SMA_20 means 20 days instead of 80 hours (3.3 days)
- **RSI Periods**: RSI_14 means 14 days instead of 56 hours (2.3 days)  
- **Volatility Windows**: 20-period volatility covers a month instead of 3.3 days
- **Support/Resistance**: Calculated over wrong time horizons

### Prediction Target Issues
- **Daily Models**: Predict next day's return (~0.1-0.3% moves)
- **4-Hour Models**: Should predict next 4 hours (~0.02-0.08% moves)
- **Scale Mismatch**: 6x difference in prediction horizons

### Trading Frequency Issues
- **Daily**: Maximum 1 trade per day per symbol
- **4-Hour**: Up to 6 trading opportunities per day
- **Opportunity Cost**: Missing 83% of potential trading signals

## 4-Hour Alignment Strategy

### 1. Data Aggregation (✅ Implemented)
```python
# Convert minute data to 4-hour bars
# Sessions: Asian1 (00:00), Asian2 (04:00), London1 (08:00), 
#          London2 (12:00), NewYork1 (16:00), NewYork2 (20:00)
```

### 2. Economic Indicator Interpolation (✅ Implemented)
- Forward-fill daily indicators to 4-hour frequency
- Add intraday momentum indicators
- Calculate gradual changes throughout the day

### 3. Feature Engineering Adjustments (✅ Implemented)
| Daily Period | 4-Hour Equivalent | Represents |
|--------------|-------------------|------------|
| 5 days | 30 bars | 1 week |
| 10 days | 60 bars | 2 weeks |
| 20 days | 120 bars | 1 month |
| 50 days | 300 bars | 2.5 months |
| 200 days | 1200 bars | 10 months |

### 4. Model Retraining Requirements
- Adjust all period parameters to 4-hour equivalents
- Scale prediction targets appropriately
- Increase training data (6x more bars)
- Adjust confidence thresholds for smaller moves

### 5. Backtesting Modifications
- Execute trades every 4 hours instead of daily
- Adjust position holding periods
- Update risk calculations for intraday volatility
- Implement session-specific strategies

## Expected Improvements

### 1. More Trading Opportunities
- From 1 signal/day to 6 signals/day
- Better capture of intraday trends
- Ability to exit losing positions faster

### 2. Better Feature Relevance
- Technical indicators at correct timeframes
- Proper momentum and mean reversion signals
- Session-based patterns (Asian range, London breakout, NY reversal)

### 3. Improved Risk Management
- Faster stop-loss triggers
- Dynamic position sizing based on session volatility
- Better drawdown control

### 4. Higher Signal Quality
- Features calculated at intended frequencies
- Predictions at appropriate time horizons
- Reduced lag in signal generation

## Implementation Steps

1. **Process Historical Data** (align_to_4hour_system.py)
   - Aggregate all minute data to 4-hour bars
   - Interpolate economic indicators
   - Create session-aware features

2. **Train New Models** (train_4hour_models.py)
   ```bash
   ./venv/bin/python scripts/train_4hour_models.py
   ```

3. **Update Backtesting Engine** (backtest_4hour_system.py)
   ```bash
   ./venv/bin/python scripts/backtest_4hour_system.py
   ```

4. **Optimize Strategies**
   - Session-specific entry/exit rules
   - Volatility-based position sizing
   - Correlation adjustments for 4-hour timeframe

## Performance Expectations

### Current (Daily)
- 4 trades in 2 years
- -1.41% return
- 448-day average holding period
- 25% win rate

### Expected (4-Hour)
- 200-500 trades in 2 years
- 5-15% annual return
- 2-10 day average holding period
- 45-55% win rate
- Sharpe ratio > 1.5

## Risk Considerations

1. **Increased Transaction Costs**: More trades = higher costs
2. **Slippage**: 4-hour bars may have less liquidity
3. **Overtrading**: Need strict signal quality filters
4. **System Complexity**: More data, more features, more decisions

## Conclusion

The 4-hour alignment is critical for the system to function as designed. This isn't just an optimization - it's fixing a fundamental architectural mismatch that was preventing the system from working properly.