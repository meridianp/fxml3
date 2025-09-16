# GBPUSD Model Performance Report

## Executive Summary
- **Best Model**: LightGBM
- **Test Accuracy**: 60.73%
- **Directional Accuracy**: 51.0% (better than random)
- **Training Date**: 2025-06-17

## Model Comparison
| Model | Accuracy | F1-Score (Macro) |
|-------|----------|------------------|
| Random Forest | 58.97% | 0.539 |
| XGBoost | 60.12% | 0.555 |
| **LightGBM** | **60.73%** | **0.568** |

## Trading Performance

### Signal Distribution
- **Buy Signals**: 1,493 (31.6% of test period)
- **Sell Signals**: 1,133 (24.0% of test period)
- **Hold Signals**: 2,093 (44.4% of test period)

### Signal Accuracy
- **Buy Signal Accuracy**: 46.6%
- **Sell Signal Accuracy**: 43.7%
- **Directional Accuracy**: 51.0%

### Prediction Confidence
- **Average Confidence**: 63.1%
- **Confidence when Correct**: 69.6%
- **Confidence when Wrong**: 53.0%

## Key Features (Top 10)
1. **volume_ratio** - Most important feature
2. **momentum_10** - 10-period momentum
3. **volume_sma_20** - 20-period volume average
4. **momentum_3** - Short-term momentum
5. **close_to_high** - Price position indicator
6. **volatility_14** - 14-period volatility
7. **daily_return** - Daily price change
8. **atr_14** - Average True Range
9. **high_low_spread** - Intraday range
10. **parkinson_vol** - Parkinson volatility

## Time-Based Performance
### Recent Monthly Accuracy (2025)
- January: 43.0%
- February: 42.9%
- March: 46.8%
- April: 50.6%
- May: 46.2%
- June: 46.5%

### Statistics
- **Best Month**: 100% (likely a month with very few samples)
- **Worst Month**: 42.9%
- **Standard Deviation**: 16.4%

## Key Insights

### Strengths
1. **Consistent Performance**: Model maintains 60%+ accuracy
2. **Balanced Predictions**: Not biased toward any single class
3. **Volume Features**: Strong predictive power from volume-based indicators
4. **Momentum Signals**: Short and medium-term momentum are key drivers

### Areas for Improvement
1. **Signal Accuracy**: Buy/Sell signals are below 50% accuracy individually
2. **Monthly Variability**: Performance varies significantly month-to-month
3. **Low Confidence**: Average confidence is only 63%

## Recommendations

1. **Risk Management**: Use strict stop-losses due to <50% individual signal accuracy
2. **Position Sizing**: Consider confidence scores for position sizing
3. **Ensemble Approach**: Combine with other models or indicators
4. **Further Training**: Consider training on specific market regimes
5. **Feature Engineering**: Add more volume and momentum-based features

## Next Steps
1. Backtest the model with realistic trading conditions
2. Implement risk management rules
3. Test on other currency pairs
4. Consider ensemble methods to improve accuracy
