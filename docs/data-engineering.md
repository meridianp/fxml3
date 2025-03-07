# Data Engineering Module

The Data Engineering module is responsible for acquiring, cleaning, preprocessing, and feature engineering forex data for Elliott Wave analysis.

## Component Overview

![Data Engineering Components](assets/data_engineering_components.png)

The Data Engineering module consists of these main components:

1. **Data Feeds**: Adapters for different data sources (Yahoo Finance, FXCM, Interactive Brokers, CSV)
2. **Data Loader**: Unified API for loading data from any feed
3. **Preprocessing**: Data cleaning, normalization, and resampling
4. **Feature Engineering**: Extraction of features for Elliott Wave analysis
5. **Data Pipeline**: End-to-end workflow for data processing

## Data Feeds

The Data Feeds component provides a standardized interface for retrieving data from different sources. All data feeds implement the `DataFeed` abstract base class.

### Available Data Feeds

- **YahooDataFeed**: Retrieves data from Yahoo Finance (free, no account required)
- **CSVDataFeed**: Loads data from local CSV files
- **FXCMDataFeed**: Connects to FXCM API (requires FXCM account)
- **IBDataFeed**: Interfaces with Interactive Brokers (requires IB account)

### Using Data Feeds

```python
from fxml3.data_engineering.data_feeds import create_data_feed

# Create a Yahoo Finance feed
yahoo_feed = create_data_feed("yahoo", cache_dir="data/cache")

# Get historical data
data = yahoo_feed.get_historical_data(
    symbol="EURUSD=X",  # Symbol to fetch
    start_date="2023-01-01",  # Start date
    end_date="2023-12-31",  # End date
    timeframe="1d",  # Timeframe
)
```

### Common Data Feed Interface

All data feeds implement these core methods:

- `get_historical_data()`: Retrieve historical OHLCV data for a symbol
- `get_latest_data()`: Get the most recent N bars for a symbol
- `standardize_symbol()`: Convert generic symbols to feed-specific format
- `standardize_timeframe()`: Convert generic timeframes to feed-specific format

Optional methods (depending on feed capabilities):
- `get_available_symbols()`: List available symbols
- `is_market_open()`: Check if the market is currently open
- `get_account_info()`: Get account information (for trading-enabled feeds)
- `place_order()`, `get_orders()`, `cancel_order()`, `get_positions()`: Trading methods

## Data Loader

The Data Loader provides a higher-level interface for working with data feeds:

```python
from fxml3.data_engineering.data_loader import ForexDataLoader

# Create a data loader with Yahoo Finance as the source
loader = ForexDataLoader(data_source="yahoo", cache_dir="data/cache")

# Load data
data = loader.load_data(
    symbol="EURUSD",
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1D",
)

# Switch to a different data source
loader.change_data_source("csv", data_dir="data/csv")
```

The Data Loader abstracts away the details of specific data feeds, providing a consistent interface regardless of the underlying data source.

## Preprocessing

The Preprocessing component handles data cleaning, normalization, and resampling:

### Data Cleaning

The `clean_data()` function handles:
- Missing value imputation (forward filling price data)
- OHLC relationship validation (ensuring high ≥ open, close ≥ low, etc.)
- Outlier detection and handling

### Normalization

The `normalize_data()` function supports multiple normalization methods:
- Min-max scaling: Scale data to a specific range (default 0-1)
- Z-score normalization: Standardize data based on mean and standard deviation
- Decimal scaling: Normalize by dividing by powers of 10

### Resampling

The `resample_data()` function allows changing the timeframe of data:
- Convert between any timeframes (e.g., 1-minute → 5-minute → 1-hour → daily)
- Proper OHLC aggregation (open=first, high=max, low=min, close=last)
- Volume aggregation (sum)

### Technical Indicators

The `add_technical_indicators()` function adds common indicators using pandas-ta:
- Moving averages (SMA, EMA)
- Oscillators (RSI, MACD)
- Volatility indicators (Bollinger Bands, ATR)
- Trend indicators (ADX)

## Feature Engineering

The Feature Engineering component extracts specific features for Elliott Wave analysis:

### Candlestick Patterns

The `extract_candlestick_patterns()` function extracts:
- Body size features (absolute and relative)
- Shadow features (upper and lower)
- Candlestick patterns (doji, hammer, shooting star, engulfing)

### Fibonacci Features

The `extract_fibonacci_features()` function extracts:
- Fibonacci retracement levels
- Proximity to Fibonacci levels
- Relative position within Fibonacci ranges

### Trend Features

The `extract_trend_features()` function extracts:
- Moving average crossovers
- Price relative to moving averages
- Trend strength indicators

### Wave Features

The `extract_wave_features()` function extracts:
- Peak and trough identification
- Wave classification (impulse vs. corrective)
- Wave properties (length, size, relative size)

## Data Pipeline

The Data Pipeline provides an end-to-end workflow for data processing:

```python
from fxml3.data_engineering.pipeline import DataPipeline

# Initialize the pipeline
pipeline = DataPipeline(data_source="yahoo", cache_dir="data/cache")

# Configure the pipeline
pipeline.set_config(
    clean_data=True,
    add_indicators=True,
    normalize=False,
    add_candlestick_patterns=True,
    add_fibonacci_features=True,
    add_trend_features=True,
    add_wave_features=False,
    indicators=["sma", "ema", "rsi", "macd", "bollinger"],
    periods=[14, 20, 50, 200],
    resampled_timeframe="4h",
)

# Process data for a single symbol
data, metadata = pipeline.process(
    symbol="EURUSD",
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1h",
)

# Process multiple symbols
results = pipeline.process_multiple(
    symbols=["EURUSD", "GBPUSD", "USDJPY"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1d",
)
```

The pipeline output includes both the processed data and metadata about the processing steps, which is useful for tracking transformations and for reproducibility.

## Performance Considerations

For optimal performance when working with the Data Engineering module:

1. **Use caching**: Enable caching for data feeds to reduce API calls and speed up repeated access
2. **Be selective with features**: Only extract the features you need
3. **Preprocess first, then extract features**: Clean and normalize data before feature extraction
4. **Batch process multiple symbols**: Use `process_multiple()` for better efficiency
5. **Consider timeframe needs**: Use higher timeframes when possible for faster processing

## Next Steps

After processing data with the Data Engineering module, you can:

1. Use the [Visualization](visualization.md) module to create interactive charts
2. Feed the processed data into the [Elliott Wave Analysis](elliott-wave-analysis.md) module
3. Export the data for use in external applications