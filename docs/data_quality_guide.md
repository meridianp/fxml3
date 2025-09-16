# Data Quality Assessment Guide

This guide covers the data quality assessment functionality in FXML4, which helps ensure the integrity and reliability of financial market data used for backtesting and analysis.

## Overview

The data quality assessment system analyzes market data for various issues such as:

- **Missing data** - Gaps, incomplete days, and timeframe inconsistencies
- **Price anomalies** - Spikes, freezes, and unrealistic movements
- **Data integrity issues** - Invalid OHLC relationships, zeros, NaNs
- **Low volatility periods** - Suspicious lack of price movement

## Quality Metrics

The system evaluates five main quality categories:

1. **Completeness** - How much data is present versus what is expected
2. **Price Spikes** - Detection of abnormal price jumps and outliers
3. **Price Freezes** - Identification of suspicious periods with identical prices
4. **OHLC Integrity** - Verification of Open-High-Low-Close price relationships
5. **Volatility** - Analysis of price movement within expected ranges

Each category is scored from 0-100, with 100 being perfect quality. These scores are combined into an overall quality score.

## Using the Data Quality Tool

### Basic Usage

To perform a basic quality assessment:

```bash
python scripts/data_quality_check.py --pairs EURUSD GBPUSD --days 7
```

This will analyze the last 7 days of data for EUR/USD and GBP/USD.

### Advanced Options

```bash
python scripts/data_quality_check.py \
  --pairs EURUSD GBPUSD USDJPY \
  --timeframe 1h \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --input-dir /path/to/data \
  --output-dir /path/to/output \
  --report-format markdown \
  --include-details \
  --spike-threshold 0.03 \
  --freeze-threshold 15 \
  --volatility-threshold 0.0002
```

### Output Files

The tool generates two main output files:

1. **Quality Report** - A detailed assessment in markdown or JSON format
2. **Quality Visualization** - A graphical overview of data quality over time

### Integration with Scheduled Updates

The quality assessment is integrated into the scheduled data update workflow:

```bash
python scripts/scheduled_data_update.py --quality-days 10 --timeframe 1h
```

This runs the regular data update and then performs quality assessment on the most recent 10 days of data at the 1-hour timeframe.

## Interpreting Quality Scores

### Overall Quality Score

| Score Range | Quality Level | Recommendation |
|-------------|---------------|----------------|
| 90-100      | Excellent     | Ideal for production use |
| 70-90       | Good          | Suitable for most purposes |
| 50-70       | Moderate      | Use with caution, may need cleaning |
| 30-50       | Poor          | Requires attention before use |
| 0-30        | Very Poor     | Not recommended for use |

### Category-Specific Issues

#### Low Completeness Score

A low completeness score indicates missing data:

- Check for gaps in the data
- Verify data source connectivity
- Consider adjusting market hours configuration
- Backfill missing periods

#### Price Spike Issues

Suspicious price spikes may indicate:

- Data feed errors or glitches
- Legitimate but extreme market events
- Mixing of data from different sources
- Tick data anomalies

#### OHLC Integrity Problems

Low OHLC integrity scores point to:

- Data corruption issues
- Feed provider problems
- Import/conversion errors
- Zero or negative values

#### Price Freeze Detection

Extended price freezes could mean:

- Market closes not properly handled
- Data feed interruptions
- Stale quotes from provider
- Very low liquidity periods

#### Volatility Concerns

Abnormal volatility patterns suggest:

- Potential market manipulation
- Synthetic or generated data
- Incorrect scaling or normalization
- Weekend or holiday data issues

## Customizing Quality Thresholds

You can adjust the quality assessment thresholds to match your specific requirements. The default thresholds are:

```python
DEFAULT_QUALITY_THRESHOLDS = {
    "price_spike": 0.02,        # 2% change threshold for detecting price spikes
    "price_freeze": 20,         # 20 consecutive identical prices = freeze
    "low_volatility": 0.0001,   # 0.01% minimum acceptable volatility
    "min_data_points": {
        "1m": 1000,             # Minimum data points per day for 1-minute data
        "5m": 200,              # Minimum data points per day for 5-minute data
        "15m": 70,              # Minimum data points per day for 15-minute data
        "1h": 18,               # Minimum data points per day for 1-hour data
        "4h": 5,                # Minimum data points per day for 4-hour data
    },
    "ohlc_relationship": 0.95,  # 95% of candles must have valid OHLC relationships
}
```

## Automated Quality Monitoring

For production systems, it's recommended to set up automated quality monitoring:

1. Schedule regular quality assessments with `cron` or similar
2. Set threshold-based alerts for quality scores
3. Generate quality reports for periodic review
4. Track quality metrics over time for trend analysis

Example cron job to run daily quality assessment:

```
0 1 * * * cd /path/to/fxml4 && python scripts/scheduled_data_update.py --skip-gaps --skip-latest --timeframe 1h >> logs/quality_check.log 2>&1
```

## Quality Visualization Examples

The quality visualization provides three key views:

1. **Overall Quality Trend** - Shows how quality changes over time
2. **Category Scores** - Displays individual quality metrics
3. **Quality Heatmap** - Provides a visual overview of all dimensions

### Sample Visualization

![Data Quality Visualization](./assets/data_quality_sample.png)

## Advanced Data Quality Monitoring

For more advanced quality control, consider these additional steps:

1. **Cross-Source Validation** - Compare data from multiple providers
2. **Statistical Anomaly Detection** - Apply advanced statistical methods
3. **Quality-Based Filtering** - Exclude low-quality data from analysis
4. **Quality Metrics in Backtesting** - Weight backtest results by data quality
5. **Unit Test Coverage** - Comprehensive testing of quality assessment functions
6. **TimescaleDB Integration** - Store quality metrics in TimescaleDB for time series analysis

## Troubleshooting

### Common Quality Issues

1. **Weekend Data Problems**
   - Symptoms: Low completeness on weekends
   - Solution: Configure proper market hours in the quality assessment

2. **Exchange Holidays**
   - Symptoms: Missing data, quality drops on specific dates
   - Solution: Maintain a calendar of market holidays

3. **Timezone Inconsistencies**
   - Symptoms: Daily gaps at specific times
   - Solution: Ensure consistent timezone handling across data sources

4. **Major News Events**
   - Symptoms: Extreme price spikes during news releases
   - Solution: Flag these as legitimate events, not data quality issues

## Conclusion

Regular data quality assessment is critical for reliable trading system development. By integrating quality checks into your data pipeline, you can identify and address data issues before they affect your trading strategies and decisions.

For more information, see:
- [Alpha Vantage Integration](./alpha_vantage_usage.md)
- [Backfilling Guide](./backfilling_guide.md)
- [Data Engineering Documentation](./api-reference/data-engineering/data-feeds.md)
