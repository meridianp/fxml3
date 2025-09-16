# Data Feeds

The data feeds module provides implementations for fetching market data from various sources.
Each data feed implementation inherits from the `DataFeed` base class, which provides a common interface.

## Base Data Feed

::: fxml4.data_engineering.data_feeds.base_feed.DataFeed
    handler: python
    selection:
      members:
        - __init__
        - fetch_data
        - get_available_symbols
        - get_available_timeframes

## Interactive Brokers Data Feed

The Interactive Brokers data feed (`IBDataFeed`) provides access to market data through the Interactive Brokers TWS API.

::: fxml4.data_engineering.data_feeds.ib_feed.IBDataFeed
    handler: python
    selection:
      members:
        - __init__
        - connect
        - disconnect
        - fetch_data
        - get_market_data
        - get_available_symbols
        - get_available_timeframes

### Configuration

To use the Interactive Brokers data feed, you need to provide a configuration dictionary:

```python
config = {
    "host": "127.0.0.1",      # TWS host (default: 127.0.0.1)
    "port": 7497,             # TWS port (default: 7497 for paper trading)
    "client_id": 0,           # Client ID (default: 0)
    "timeout": 30,            # Connection timeout in seconds (default: 30)
    "symbols": ["EUR.USD", "GBP.USD"]  # Supported symbols (optional)
}

feed = IBDataFeed(config)
```

### Usage Example

Here's a simple example of using the IBDataFeed to fetch historical data:

```python
from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed

# Create the data feed
config = {
    "port": 7497,  # Paper trading port
    "symbols": ["GBP.USD"]
}
feed = IBDataFeed(config)

# Connect to TWS
feed.connect()

try:
    # Fetch 1-hour data for GBP/USD
    df = feed.fetch_data("GBP.USD", timeframe="1h")

    # Print the data
    print(df.head())

    # Get current market data
    market_data = feed.get_market_data("GBP.USD")
    print(f"Current bid: {market_data.get('BID')}")
    print(f"Current ask: {market_data.get('ASK')}")

finally:
    # Disconnect when done
    feed.disconnect()
```

### Prerequisites

To use the Interactive Brokers data feed, you need:

1. Interactive Brokers account (paper or live)
2. Trader Workstation (TWS) installed and running
3. TWS configured to allow API connections

For detailed setup instructions, see the [IB API Integration tutorial](../../tutorials/ib-api-integration.md).

## Other Data Feeds

### CSV Data Feed

The CSV data feed allows loading market data from CSV files.

### Yahoo Finance Data Feed

The Yahoo Finance data feed provides access to market data through the Yahoo Finance API.

### FXCM Data Feed

The FXCM data feed provides access to market data through the FXCM API.
