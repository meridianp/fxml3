# Data Feeds Module

This module provides a flexible system for retrieving financial data from various sources with a standardized interface.

## Overview

The data feeds system is designed to be modular and extensible, allowing for easy switching between different data sources without changing the rest of the application. All data feeds implement a common interface defined in the `DataFeed` base class.

## Available Data Feeds

- **YahooDataFeed**: Retrieves data from Yahoo Finance API (free, no account required)
- **CSVDataFeed**: Loads data from local CSV files
- **FXCMDataFeed**: Integrates with FXCM API (requires FXCM account)
- **IBDataFeed**: Connects to Interactive Brokers (requires IB account)

## Usage

### Basic Usage

```python
from fxml3.data_engineering.data_feeds import create_data_feed

# Create a Yahoo Finance feed
yahoo_feed = create_data_feed("yahoo", cache_dir="data/cache")

# Get historical data
data = yahoo_feed.get_historical_data(
    symbol="EURUSD",
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1D"
)

# Get latest data
latest = yahoo_feed.get_latest_data(
    symbol="EURUSD",
    bars=10,
    timeframe="1H"
)
```

### Using the ForexDataLoader

For most users, it's recommended to use the `ForexDataLoader` class, which provides a higher-level interface:

```python
from fxml3.data_engineering.data_loader import ForexDataLoader

# Create a data loader with Yahoo Finance as the source
loader = ForexDataLoader(data_source="yahoo", cache_dir="data/cache")

# Load data
data = loader.load_data(
    symbol="EURUSD",
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1D"
)

# Switch to a different data source
loader.change_data_source("csv", data_dir="data/csv")
```

## Data Feed Configuration

### Yahoo Finance

```python
yahoo_feed = create_data_feed(
    "yahoo",
    cache_dir="data/cache"  # Optional, for caching data
)
```

### CSV Files

```python
csv_feed = create_data_feed(
    "csv",
    data_dir="data/csv",                     # Directory containing CSV files
    filename_pattern="{symbol}_{timeframe}.csv",  # Pattern for CSV filenames
    date_column="datetime",                 # Name of the date column
    datetime_format="%Y-%m-%d %H:%M:%S"     # Format of dates in the CSV
)
```

### FXCM

```python
fxcm_feed = create_data_feed(
    "fxcm",
    api_key="your_api_key",           # Or use FXCM_API_KEY env var
    access_token="your_access_token", # Or use FXCM_ACCESS_TOKEN env var
    demo=True,                        # Use demo account (True) or live (False)
    cache_dir="data/cache"            # Optional, for caching data
)
```

### Interactive Brokers

```python
ib_feed = create_data_feed(
    "ib",
    account_id="your_account_id",  # Or use IB_ACCOUNT_ID env var
    host="127.0.0.1",             # TWS/IB Gateway host
    port=7497,                    # TWS/IB Gateway port
    client_id=1,                  # Client ID for IB connection
    cache_dir="data/cache"        # Optional, for caching data
)
```

## Environment Variables

All data feeds support configuration via environment variables. You can create a `.env` file in the project root with the following variables:

```
# Data Feed Credentials
FOREX_API_KEY=your_forex_api_key_here
FXCM_API_KEY=your_fxcm_api_key_here
FXCM_ACCESS_TOKEN=your_fxcm_access_token_here
IB_ACCOUNT_ID=your_ib_account_id_here

# Data Settings
DATA_SOURCE=yahoo  # yahoo, fxcm, ib, csv
DATA_CACHE_DIR=data/cache
CSV_DATA_DIR=data/csv
```

## Extending with New Data Feeds

To add a new data feed:

1. Create a new class that inherits from `DataFeed`
2. Implement the required methods (`get_historical_data`, `get_latest_data`)
3. Add your feed to the factory function in `__init__.py`

Example:

```python
from fxml3.data_engineering.data_feeds.base_feed import DataFeed

class MyCustomFeed(DataFeed):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Your initialization code
        
    def get_historical_data(self, symbol, start_date, end_date=None, 
                            timeframe="1D", include_after_hours=False):
        # Your implementation
        pass
        
    def get_latest_data(self, symbol, bars=1, timeframe="1D"):
        # Your implementation
        pass
```

Then add it to the factory function:

```python
def create_data_feed(source_type, **kwargs):
    source_map = {
        "yahoo": YahooDataFeed,
        "csv": CSVDataFeed,
        "mycustom": MyCustomFeed,  # Add your feed here
    }
    # ...
```