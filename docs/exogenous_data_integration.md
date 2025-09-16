# Exogenous Data Integration Guide

This document outlines how to integrate exogenous data sources into the FXML4 platform to enhance trading signals and market analysis.

## Overview

Exogenous data refers to external factors that can influence financial markets, including:

1. Macroeconomic indicators (GDP, inflation, unemployment, etc.)
2. Commodity prices (oil, gold, etc.)
3. Market sentiment data (news sentiment, social media)
4. Interest rates and yield curves
5. Currency strength indicators

FXML4 integrates exogenous data from multiple sources to provide a comprehensive view of market conditions.

## Data Sources

### Alpha Vantage API

Alpha Vantage provides a comprehensive set of financial data APIs, including economic indicators, forex, crypto, and technical indicators. We use it for both market data and economic indicators.

#### Economic Indicators

Alpha Vantage offers several economic indicator endpoints:

| Endpoint | Description | Data Frequency |
|----------|-------------|----------------|
| `/REAL_GDP` | US Real Gross Domestic Product | Annual, Quarterly |
| `/REAL_GDP_PER_CAPITA` | US Real GDP per Capita | Quarterly |
| `/TREASURY_YIELD` | US Treasury Yields | Daily, Weekly, Monthly |
| `/FEDERAL_FUNDS_RATE` | US Federal Funds Rate | Daily, Weekly, Monthly |
| `/CPI` | US Consumer Price Index | Monthly, Semiannual |
| `/INFLATION` | US Inflation Rate | Annual |
| `/RETAIL_SALES` | US Retail Sales | Monthly |
| `/DURABLES` | US Durable Goods Orders | Monthly |
| `/UNEMPLOYMENT` | US Unemployment Rate | Monthly |
| `/NONFARM_PAYROLL` | US Nonfarm Payroll | Monthly |

#### Usage Example

```python
from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed

# Initialize the Alpha Vantage data feed
av_feed = AlphaVantageDataFeed(config={
    "api_key": "YOUR_API_KEY",  # Use environment variable in production
    "output_format": "pandas"
})

# Get GDP data
gdp_data = av_feed.get_economic_indicator(
    indicator="REAL_GDP",
    interval="quarterly"
)

# Get inflation data
inflation_data = av_feed.get_economic_indicator(
    indicator="INFLATION"
)

# Get unemployment data for the last 5 years
unemployment_data = av_feed.get_economic_indicator(
    indicator="UNEMPLOYMENT",
    outputsize="full"  # For full history
)

# Filter to last 5 years
import datetime
five_years_ago = datetime.datetime.now() - datetime.timedelta(days=365*5)
unemployment_data = unemployment_data[unemployment_data.index >= five_years_ago]
```

#### Commodities Data

Alpha Vantage also provides commodity price data:

| Endpoint | Description | Data Frequency |
|----------|-------------|----------------|
| `/WTI` | West Texas Intermediate (WTI) Crude Oil Prices | Daily, Weekly, Monthly |
| `/BRENT` | Brent Crude Oil Prices | Daily, Weekly, Monthly |
| `/NATURAL_GAS` | Natural Gas Prices | Daily, Weekly, Monthly |
| `/COPPER` | Copper Prices | Monthly, Quarterly, Annual |
| `/ALUMINUM` | Aluminum Prices | Monthly, Quarterly, Annual |
| `/WHEAT` | Wheat Prices | Monthly, Quarterly, Annual |
| `/CORN` | Corn Prices | Monthly, Quarterly, Annual |
| `/COTTON` | Cotton Prices | Monthly, Quarterly, Annual |
| `/SUGAR` | Sugar Prices | Monthly, Quarterly, Annual |
| `/COFFEE` | Coffee Prices | Monthly, Quarterly, Annual |
| `/ALL_COMMODITIES` | Global Commodity Price Index | Monthly, Quarterly, Annual |

### FRED API (Federal Reserve Economic Data)

The FRED API provides access to over 800,000 US and international economic time series from more than 100 sources. It's particularly valuable for detailed US economic data.

#### Key Economic Series

| Series ID | Description | Source |
|-----------|-------------|--------|
| `GDP` | Gross Domestic Product | US Bureau of Economic Analysis |
| `UNRATE` | Unemployment Rate | US Bureau of Labor Statistics |
| `CPIAUCSL` | Consumer Price Index for All Urban Consumers: All Items | US Bureau of Labor Statistics |
| `FEDFUNDS` | Federal Funds Effective Rate | Board of Governors of the Federal Reserve System |
| `T10Y2Y` | 10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity | Federal Reserve Bank of St. Louis |
| `T10Y3M` | 10-Year Treasury Constant Maturity Minus 3-Month Treasury Constant Maturity | Federal Reserve Bank of St. Louis |
| `DTWEXBGS` | Trade Weighted U.S. Dollar Index: Broad, Goods and Services | Board of Governors of the Federal Reserve System |
| `VIXCLS` | CBOE Volatility Index: VIX | Chicago Board Options Exchange |
| `M2SL` | M2 Money Stock | Board of Governors of the Federal Reserve System |
| `BAMLH0A0HYM2` | ICE BofA US High Yield Index Option-Adjusted Spread | ICE Data Indices, LLC |

#### Usage Example

```python
from fxml4.data_engineering.data_feeds.fred_feed import FREDDataFeed

# Initialize the FRED data feed
fred_feed = FREDDataFeed(config={
    "api_key": "YOUR_FRED_API_KEY"  # Use environment variable in production
})

# Get unemployment rate data
unemployment = fred_feed.get_series(
    series_id="UNRATE",
    start_date="2010-01-01"
)

# Get yield curve spread (10Y-2Y)
yield_curve = fred_feed.get_series(
    series_id="T10Y2Y",
    frequency="m"  # Monthly data
)

# Get multiple series at once
macro_data = fred_feed.get_multiple_series(
    series_ids=["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS"],
    start_date="2015-01-01",
    end_date="2025-01-01"
)
```

## Integration Strategy

Our exogenous data integration strategy follows these steps:

1. **Data Collection**: Regular fetching of exogenous data from Alpha Vantage and FRED APIs
2. **Storage**: Storing data in TimescaleDB for efficient time-series queries
3. **Feature Engineering**: Converting raw data into meaningful features
4. **Signal Generation**: Using exogenous data to enhance trading signals
5. **Backtesting**: Evaluating the impact of exogenous data on trading performance

### Storage Schema

Exogenous data is stored in the following TimescaleDB table:

```sql
CREATE TABLE exogenous_data (
    time TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,         -- 'alpha_vantage', 'fred', etc.
    indicator_name TEXT NOT NULL, -- 'REAL_GDP', 'UNRATE', etc.
    value DOUBLE PRECISION NOT NULL,
    frequency TEXT NOT NULL,      -- 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
    metadata JSONB,

    PRIMARY KEY (time, source, indicator_name)
);

-- Convert to hypertable
SELECT create_hypertable('exogenous_data', 'time');

-- Create index for faster queries
CREATE INDEX idx_exogenous_data_indicator ON exogenous_data (indicator_name, time DESC);
```

### Refresh Schedule

Different economic indicators are updated at different frequencies:

- Daily: Interest rates, commodity prices (WTI, Brent, natural gas)
- Weekly: Some Fed data, treasury yields
- Monthly: CPI, unemployment, retail sales, nonfarm payroll
- Quarterly: GDP, other major economic indicators
- Annual: Some GDP measures, long-term economic trends

Our data collectors run on the following schedule:

```python
# Schedule configuration
REFRESH_SCHEDULE = {
    "daily": {
        "indicators": ["FEDERAL_FUNDS_RATE", "TREASURY_YIELD", "WTI", "BRENT",
                     "NATURAL_GAS", "DTWEXBGS", "VIXCLS"],
        "time": "18:00:00"  # After US market close
    },
    "weekly": {
        "indicators": ["T10Y2Y", "T10Y3M", "BAMLH0A0HYM2"],
        "day": "Friday",
        "time": "18:00:00"
    },
    "monthly": {
        "indicators": ["CPI", "UNEMPLOYMENT", "RETAIL_SALES", "DURABLES",
                      "NONFARM_PAYROLL", "M2SL"],
        "day": 15,  # Middle of the month, after most releases
        "time": "12:00:00"
    },
    "quarterly": {
        "indicators": ["REAL_GDP", "REAL_GDP_PER_CAPITA", "GDP"],
        "months": [1, 4, 7, 10],  # January, April, July, October
        "day": 30,
        "time": "12:00:00"
    }
}
```

## Feature Engineering

Raw economic data is transformed into features relevant for trading:

### Rate of Change Features

```python
# Calculate month-over-month percent change
df['mom_pct_change'] = df['value'].pct_change()

# Calculate year-over-year percent change
df['yoy_pct_change'] = df['value'].pct_change(12)  # For monthly data

# Calculate rate of change relative to historical percentiles
df['percentile_rank'] = df['value'].rolling(window=60).apply(
    lambda x: pd.Series(x).rank(pct=True).iloc[-1]
)
```

### Trend and Momentum Features

```python
# Moving averages
df['ma_3m'] = df['value'].rolling(window=3).mean()
df['ma_12m'] = df['value'].rolling(window=12).mean()

# Trend direction
df['trend'] = np.where(df['ma_3m'] > df['ma_12m'], 1, -1)

# Standardized momentum
df['momentum'] = (df['value'] - df['ma_12m']) / df['value'].rolling(window=12).std()
```

### Surprise and Deviation Features

```python
# Calculate surprise vs expectations (for indicators with forecasts)
df['surprise'] = df['actual'] - df['forecast']
df['surprise_std'] = df['surprise'] / df['surprise'].rolling(window=12).std()

# Z-score (standardized deviation from mean)
df['z_score'] = (df['value'] - df['value'].rolling(window=60).mean()) / df['value'].rolling(window=60).std()
```

## Application in Trading Strategies

Exogenous data can be used in trading strategies in several ways:

### Regime Detection

```python
def detect_economic_regime(data):
    """
    Detect economic regime based on multiple indicators.

    Returns:
        str: 'expansion', 'contraction', 'recovery', or 'stagflation'
    """
    # Simplified example - in practice, use more indicators and sophisticated methods
    gdp_growing = data['REAL_GDP']['yoy_pct_change'].iloc[-1] > 0
    inflation_high = data['CPI']['yoy_pct_change'].iloc[-1] > 0.03  # 3% threshold
    unemployment_high = data['UNEMPLOYMENT']['value'].iloc[-1] > 0.05  # 5% threshold

    if gdp_growing and not inflation_high:
        return 'expansion'
    elif not gdp_growing and not inflation_high:
        return 'contraction'
    elif gdp_growing and inflation_high:
        return 'recovery'
    else:  # not gdp_growing and inflation_high
        return 'stagflation'
```

### Signal Modification

```python
def adjust_signal_for_economic_conditions(base_signal, exogenous_features):
    """
    Adjust trading signal based on economic conditions.

    Args:
        base_signal (float): Original trading signal (-1.0 to 1.0)
        exogenous_features (dict): Dictionary of exogenous features

    Returns:
        float: Adjusted trading signal
    """
    # Example adjustments based on economic indicators

    # Reduce position size during high volatility periods
    if exogenous_features['VIX'] > 30:
        base_signal *= 0.5

    # Reduce long exposure during yield curve inversions
    if exogenous_features['T10Y2Y'] < 0:
        base_signal = min(base_signal, 0.5)

    # Increase conviction during clear trends
    if exogenous_features['economic_regime'] == 'expansion' and base_signal > 0:
        base_signal *= 1.2
    elif exogenous_features['economic_regime'] == 'contraction' and base_signal < 0:
        base_signal *= 1.2

    # Cap signal between -1.0 and 1.0
    return max(min(base_signal, 1.0), -1.0)
```

### Feature Importance Analysis

We regularly analyze which exogenous features have the most impact on our trading signals and performance:

```python
def analyze_feature_importance(features, returns):
    """
    Analyze the importance of exogenous features for predicting returns.

    Args:
        features (DataFrame): Exogenous features
        returns (Series): Asset returns

    Returns:
        DataFrame: Feature importance scores
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.inspection import permutation_importance

    # Train a model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(features, returns)

    # Get feature importance
    result = permutation_importance(model, features, returns, n_repeats=10, random_state=42)

    # Create DataFrame of importance scores
    importance_df = pd.DataFrame({
        'Feature': features.columns,
        'Importance': result.importances_mean,
        'Std': result.importances_std
    }).sort_values('Importance', ascending=False)

    return importance_df
```

## Next Steps

Our roadmap for enhancing exogenous data integration includes:

1. **Sentiment Analysis**: Adding news sentiment and social media indicators
2. **Alternative Data**: Incorporating satellite imagery, credit card spending data, etc.
3. **Market Microstructure**: Including order flow and liquidity metrics
4. **Global Economic Data**: Expanding beyond US-centric indicators to global markets
5. **Lead-Lag Analysis**: Identifying leading indicators for different market regimes
